# Registry Expansion — Batch 3 (Verified CLI Tools) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Grow the registry from 25 to 37 tools by adding 12 more verified AI-dev CLIs, reusing the existing download path (no executor changes).

**Architecture:** Pure declarative data, same as Batch 2. Each tool is `github_release` (OS-split) + `brew`, except the four `raw` single-binary tools (shfmt, tealdeer, fx, dasel). Every asset/strip/member verified against live releases on 2026-06-10. Tools whose assets use non-standard arch tokens (`x64`, `64-bit`) or `.zip`/`.tar.xz`/bare-`.gz` formats were deliberately excluded (see Deferred).

**Tech Stack:** Python 3.11+, uv, tomllib, pytest (100% coverage gate), ruff/pyright-strict/bandit/vulture.

---

## Verified Release Facts (live releases, 2026-06-10)

`{ver}` = tag without leading `v`. Tokens: amd64 → machine=`x86_64`, deb=`amd64`, suffix=`x86_64`; arm64 → machine=`aarch64`, deb=`arm64`, suffix=`arm64`.

| tool | repo | id | cmd | cat | linux asset | macOS asset | strip | member | raw | brew |
|---|---|---|---|---|---|---|---|---|---|---|
| gitui | extrawurst/gitui | gitui | gitui | git | `gitui-linux-{arch.machine}.tar.gz` | *(none — brew)* | 0 | gitui | no | gitui |
| lazydocker | jesseduffield/lazydocker | lazydocker | lazydocker | docker | `lazydocker_{ver}_Linux_{arch.suffix}.tar.gz` | `lazydocker_{ver}_Darwin_{arch.suffix}.tar.gz` | 0 | lazydocker | no | lazydocker |
| dive | wagoodman/dive | dive | dive | docker | `dive_{ver}_linux_{arch.deb}.tar.gz` | `dive_{ver}_darwin_{arch.deb}.tar.gz` | 0 | dive | no | dive |
| duf | muesli/duf | duf | duf | sysinfo | `duf_{ver}_linux_{arch.suffix}.tar.gz` | `duf_{ver}_darwin_{arch.suffix}.tar.gz` | 0 | duf | no | duf |
| hexyl | sharkdp/hexyl | hexyl | hexyl | view | `hexyl-v{ver}-{arch.machine}-unknown-linux-gnu.tar.gz` | `hexyl-v{ver}-{arch.machine}-apple-darwin.tar.gz` | 1 | hexyl | no | hexyl |
| miller | johnkerl/miller | miller | mlr | data | `miller-{ver}-linux-{arch.deb}.tar.gz` | `miller-{ver}-darwin-{arch.deb}.tar.gz` | 1 | mlr | no | miller |
| shfmt | mvdan/sh | shfmt | shfmt | dev | `shfmt_v{ver}_linux_{arch.deb}` | `shfmt_v{ver}_darwin_{arch.deb}` | — | shfmt | **yes** | shfmt |
| tealdeer | dbrgn/tealdeer | tealdeer | tldr | dev | `tealdeer-linux-{arch.machine}-musl` | `tealdeer-macos-{arch.machine}` | — | tldr | **yes** | tealdeer |
| fx | antonmedv/fx | fx | fx | data | `fx_linux_{arch.deb}` | `fx_darwin_{arch.deb}` | — | fx | **yes** | fx |
| dasel | TomWright/dasel | dasel | dasel | data | `dasel_linux_{arch.deb}` | `dasel_darwin_{arch.deb}` | — | dasel | **yes** | dasel |
| gron | tomnomnom/gron | gron | gron | data | `gron-linux-{arch.deb}-{ver}.tgz` | `gron-darwin-{arch.deb}-{ver}.tgz` | 0 | gron | no | gron |
| aichat | sigoden/aichat | aichat | aichat | ai | `aichat-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz` | `aichat-v{ver}-{arch.machine}-apple-darwin.tar.gz` | 0 | aichat | no | aichat |

**Per-tool notes (do not "simplify"):**
- `gitui` has no clean per-arch macOS asset (`gitui-mac.tar.gz` / `gitui-mac-x86.tar.gz` don't use our tokens) → **macOS via brew only** (linux `github_release` + `brew`).
- `miller`'s binary is `mlr`; `tealdeer`'s binary is `tldr` — `cmd`/`member` differ from `id`.
- `shfmt` embeds a **literal `v`**: `shfmt_v{ver}_...` (tag `v3.13.1` → `shfmt_v3.13.1_...`). `gron` puts the version at the **end**: `gron-linux-{arch.deb}-{ver}.tgz`, and uses the `.tgz` extension (still a gzip tarball — `tar -xz` handles it).
- `hexyl` uses **gnu** (its aarch64 linux has no musl); `miller`/`hexyl` are the only `strip = 1` tools — the rest are flat (`strip = 0`).
- `shfmt`/`tealdeer`/`fx`/`dasel` are `raw = true` (single binary, no `strip`). `fx`/`dasel`/`tealdeer` embed no version in the asset name.
- `lazydocker`/`duf` use `{arch.suffix}` (`Linux_x86_64` / `Darwin_arm64`); `dive`/`gron`/`fx`/`dasel`/`shfmt`/`miller` use `{arch.deb}`.

---

## File Structure
- `installer/registry.toml` — **modify**: append 12 `[[tool]]` entries.
- `tests/test_registry.py` — **modify**: add resolution tests.
- `README.md` — **modify**: extend the "Available tools" table.
- memory `roadmap-status.md` — **modify**: record Batch 3.

---

## Task 1: Add gitui, lazydocker, dive, duf, hexyl, miller

**Files:** Modify `installer/registry.toml`; Test `tests/test_registry.py`.

- [ ] **Step 1: Append these six tools to `installer/registry.toml`:**

```toml
[[tool]]
id = "gitui"
name = "gitui"
category = "git"
cmd = "gitui"
priority = "P2"
audience = "both"
desc = "Blazing-fast terminal UI for git"
# gitui's macOS assets don't use our arch tokens, so install via brew on a Mac.
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "extrawurst/gitui"
asset = "gitui-linux-{arch.machine}.tar.gz"
member = "gitui"
strip = 0
[[tool.method]]
kind = "brew"
formula = "gitui"

[[tool]]
id = "lazydocker"
name = "lazydocker"
category = "docker"
cmd = "lazydocker"
priority = "P2"
audience = "both"
desc = "A simple terminal UI for docker and docker-compose"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "jesseduffield/lazydocker"
asset = "lazydocker_{ver}_Linux_{arch.suffix}.tar.gz"
member = "lazydocker"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "jesseduffield/lazydocker"
asset = "lazydocker_{ver}_Darwin_{arch.suffix}.tar.gz"
member = "lazydocker"
strip = 0
[[tool.method]]
kind = "brew"
formula = "lazydocker"

[[tool]]
id = "dive"
name = "dive"
category = "docker"
cmd = "dive"
priority = "P2"
audience = "both"
desc = "A tool for exploring each layer in a docker image"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "wagoodman/dive"
asset = "dive_{ver}_linux_{arch.deb}.tar.gz"
member = "dive"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "wagoodman/dive"
asset = "dive_{ver}_darwin_{arch.deb}.tar.gz"
member = "dive"
strip = 0
[[tool.method]]
kind = "brew"
formula = "dive"

[[tool]]
id = "duf"
name = "duf"
category = "sysinfo"
cmd = "duf"
priority = "P2"
audience = "both"
desc = "Disk Usage/Free utility with a friendly table view"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "muesli/duf"
asset = "duf_{ver}_linux_{arch.suffix}.tar.gz"
member = "duf"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "muesli/duf"
asset = "duf_{ver}_darwin_{arch.suffix}.tar.gz"
member = "duf"
strip = 0
[[tool.method]]
kind = "brew"
formula = "duf"

[[tool]]
id = "hexyl"
name = "hexyl"
category = "view"
cmd = "hexyl"
priority = "P2"
audience = "both"
desc = "A command-line hex viewer"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "sharkdp/hexyl"
asset = "hexyl-v{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"
member = "hexyl"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "sharkdp/hexyl"
asset = "hexyl-v{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "hexyl"
strip = 1
[[tool.method]]
kind = "brew"
formula = "hexyl"

[[tool]]
id = "miller"
name = "miller"
category = "data"
cmd = "mlr"
priority = "P2"
audience = "both"
desc = "Like awk/sed/cut/join/sort for CSV, TSV, and JSON"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "johnkerl/miller"
asset = "miller-{ver}-linux-{arch.deb}.tar.gz"
member = "mlr"
strip = 1
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "johnkerl/miller"
asset = "miller-{ver}-darwin-{arch.deb}.tar.gz"
member = "mlr"
strip = 1
[[tool.method]]
kind = "brew"
formula = "miller"
```

- [ ] **Step 2: Add resolution tests to `tests/test_registry.py`:**

```python
def test_gitui_is_linux_download_and_brew_only_on_macos() -> None:
    gitui = next(t for t in load_tools(REGISTRY) if t.id == "gitui")
    linux = Platform(os="debian", arch="aarch64" and "amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    assert [m.kind for m in resolve_methods(gitui, linux)] == ["github_release", "brew"]
    assert [m.kind for m in resolve_methods(gitui, macos)] == ["brew"]


def test_miller_cmd_is_mlr_and_strips_nested_member() -> None:
    miller = next(t for t in load_tools(REGISTRY) if t.id == "miller")
    assert miller.cmd == "mlr"
    linux = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)
    method = resolve_methods(miller, linux)[0]
    assert method.params["member"] == "mlr"
    assert method.params["strip"] == 1


def test_hexyl_linux_uses_gnu_and_strips() -> None:
    hexyl = next(t for t in load_tools(REGISTRY) if t.id == "hexyl")
    linux = Platform(os="arch", arch="arm64", immutable=False, has_brew=True)
    method = resolve_methods(hexyl, linux)[0]
    assert method.params["asset"] == "hexyl-v{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"
    assert method.params["strip"] == 1
```
NOTE: write the gitui linux platform as `Platform(os="debian", arch="amd64", immutable=False, has_brew=True)` — the `"aarch64" and "amd64"` above is a mistake; use the plain `arch="amd64"`.

- [ ] **Step 3: Run `make validate && make test`; both must pass at 100% coverage.**

- [ ] **Step 4: Commit:**
```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add gitui, lazydocker, dive, duf, hexyl and miller"
```

---

## Task 2: Add shfmt, tealdeer, fx, dasel, gron, aichat

**Files:** Modify `installer/registry.toml`; Test `tests/test_registry.py`.

- [ ] **Step 1: Append these six tools to `installer/registry.toml`:**

```toml
[[tool]]
id = "shfmt"
name = "shfmt"
category = "dev"
cmd = "shfmt"
priority = "P2"
audience = "both"
desc = "A shell parser, formatter, and interpreter (sh/bash/mksh)"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "mvdan/sh"
asset = "shfmt_v{ver}_linux_{arch.deb}"
member = "shfmt"
raw = true
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "mvdan/sh"
asset = "shfmt_v{ver}_darwin_{arch.deb}"
member = "shfmt"
raw = true
[[tool.method]]
kind = "brew"
formula = "shfmt"

[[tool]]
id = "tealdeer"
name = "tealdeer"
category = "dev"
cmd = "tldr"
priority = "P2"
audience = "both"
desc = "A fast tldr client — simplified, community-driven man pages"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "dbrgn/tealdeer"
asset = "tealdeer-linux-{arch.machine}-musl"
member = "tldr"
raw = true
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "dbrgn/tealdeer"
asset = "tealdeer-macos-{arch.machine}"
member = "tldr"
raw = true
[[tool.method]]
kind = "brew"
formula = "tealdeer"

[[tool]]
id = "fx"
name = "fx"
category = "data"
cmd = "fx"
priority = "P2"
audience = "both"
desc = "A terminal JSON viewer and processor"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "antonmedv/fx"
asset = "fx_linux_{arch.deb}"
member = "fx"
raw = true
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "antonmedv/fx"
asset = "fx_darwin_{arch.deb}"
member = "fx"
raw = true
[[tool.method]]
kind = "brew"
formula = "fx"

[[tool]]
id = "dasel"
name = "dasel"
category = "data"
cmd = "dasel"
priority = "P2"
audience = "both"
desc = "Query and modify JSON, YAML, TOML, XML, and CSV with one tool"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "TomWright/dasel"
asset = "dasel_linux_{arch.deb}"
member = "dasel"
raw = true
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "TomWright/dasel"
asset = "dasel_darwin_{arch.deb}"
member = "dasel"
raw = true
[[tool.method]]
kind = "brew"
formula = "dasel"

[[tool]]
id = "gron"
name = "gron"
category = "data"
cmd = "gron"
priority = "P2"
audience = "both"
desc = "Make JSON greppable by flattening it into discrete assignments"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "tomnomnom/gron"
asset = "gron-linux-{arch.deb}-{ver}.tgz"
member = "gron"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "tomnomnom/gron"
asset = "gron-darwin-{arch.deb}-{ver}.tgz"
member = "gron"
strip = 0
[[tool.method]]
kind = "brew"
formula = "gron"

[[tool]]
id = "aichat"
name = "aichat"
category = "ai"
cmd = "aichat"
priority = "P1"
audience = "ai"
desc = "All-in-one LLM CLI tool (chat REPL, shell assistant, RAG)"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "sigoden/aichat"
asset = "aichat-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz"
member = "aichat"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "sigoden/aichat"
asset = "aichat-v{ver}-{arch.machine}-apple-darwin.tar.gz"
member = "aichat"
strip = 0
[[tool.method]]
kind = "brew"
formula = "aichat"
```
Critical: shfmt embeds a literal `v` (`shfmt_v{ver}_...`); gron's version is at the END with a `.tgz` extension; tealdeer's binary is `tldr` (cmd ≠ id) and uses two different naming schemes per OS (`tealdeer-linux-{m}-musl` vs `tealdeer-macos-{m}`); fx/dasel/tealdeer/shfmt are `raw = true` (no `strip`). gron/aichat are archives with `strip = 0`.

- [ ] **Step 2: Add resolution tests to `tests/test_registry.py`:**

```python
def test_raw_tools_have_no_strip_and_resolve_per_os() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    expected_linux_asset = {
        "shfmt": "shfmt_v{ver}_linux_{arch.deb}",
        "tealdeer": "tealdeer-linux-{arch.machine}-musl",
        "fx": "fx_linux_{arch.deb}",
        "dasel": "dasel_linux_{arch.deb}",
    }
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=False)
    for tool_id, asset in expected_linux_asset.items():
        method = resolve_methods(tools[tool_id], linux)[0]
        assert method.params.get("raw") is True
        assert "strip" not in method.params
        assert method.params["asset"] == asset


def test_tealdeer_cmd_is_tldr_with_per_os_naming() -> None:
    tealdeer = next(t for t in load_tools(REGISTRY) if t.id == "tealdeer")
    assert tealdeer.cmd == "tldr"
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=False)
    assert resolve_methods(tealdeer, macos)[0].params["asset"] == "tealdeer-macos-{arch.machine}"


def test_gron_uses_tgz_with_trailing_version() -> None:
    gron = next(t for t in load_tools(REGISTRY) if t.id == "gron")
    linux = Platform(os="debian", arch="arm64", immutable=False, has_brew=True)
    method = resolve_methods(gron, linux)[0]
    assert method.params["asset"] == "gron-linux-{arch.deb}-{ver}.tgz"
    assert method.params["strip"] == 0


def test_registry_has_thirty_seven_unique_tools_and_cmds() -> None:
    tools = load_tools(REGISTRY)
    ids = [t.id for t in tools]
    cmds = [t.cmd for t in tools]
    assert len(ids) == 37
    assert len(ids) == len(set(ids))
    assert len(cmds) == len(set(cmds))
```

- [ ] **Step 3: Run `make validate && make test`; both must pass at 100% coverage.**

- [ ] **Step 4: Commit:**
```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add shfmt, tealdeer, fx, dasel, gron and aichat"
```

---

## Task 3: Update docs

**Files:** Modify `README.md`; Modify memory `roadmap-status.md`.

- [ ] **Step 1: Extend the README "Available tools" table** with the new tools and categories: git (`+gitui`), docker (`lazydocker`, `dive`), sysinfo (`+duf`), view (`+hexyl`), data (`+miller`/mlr, `fx`, `dasel`, `gron`), dev (`+shfmt`, `tealdeer`/tldr), ai (`aichat`). Keep existing rows; describe only what exists.

- [ ] **Step 2: Update the roadmap memory** (`/Users/ramon/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md`): record Batch 3 (registry 25→37; the 12 tools; no executor changes). Note gitui is brew-only on macOS; tealdeer→tldr and miller→mlr have cmd≠id; shfmt/tealdeer/fx/dasel are raw. Under deferred, keep/expand: zip-only and bare-`.gz`/`.tar.xz` tools (deno, bun, fnm, procs, ast-grep, jless, taplo, shellcheck-as-tool); tools using `x64`/`64-bit` arch tokens (pnpm, gitleaks, vale) — would need an `x64` token in `assets.py`; volta (no arm64 asset).

- [ ] **Step 3: Commit (README only; memory is outside the repo):**
```bash
git add README.md
git commit -m "docs: document the batch 3 tool catalog"
```

---

## Self-Review (completed by plan author)
- **Spec coverage:** 12 tools across Tasks 1–2; docs Task 3. Every asset/strip/member/raw value from the Verified Release Facts table. ✓
- **Placeholder scan:** No TBDs; all literals verified against live releases. The one deliberate inline correction (gitui test `arch`) is called out explicitly with the fix. ✓
- **Type consistency:** Methods follow the `Method` shape; raw tools omit `strip`; miller/tealdeer use cmd≠id (mlr/tldr); the count test (37) = 25 existing + 12 new. ✓
- **No executor changes:** every shape (os-split, raw, strip, .tgz, gnu/musl, trailing-version, literal-v) is already supported by the executor. ✓
