# Registry Batch 5 (x64/bits tokens + selective-zip) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Two small executor-data extensions that unlock three tools (registry 44 → 47): add `x64`/`bits` arch tokens (→ gitleaks, vale), and make `.zip` extraction selective so a single binary can be pulled from a combined multi-platform archive (→ broot).

**Architecture:** `assets.py` gains two `ArchTokens` fields rendered as `{arch.x64}`/`{arch.bits}`. The `.zip` branch of `download.py` extracts only the `member` (`unzip … <member> …`) instead of the whole archive — strictly less disk, identical resulting symlink, and it makes broot's 56 MB combined zip practical. All three tools are pure registry data on top; all asset names/layouts verified live (below).

**Tech Stack:** TOML registry, `assets.py` templating, `download.py` executor, pytest. Gates: ruff, pyright strict, bandit, vulture, shellcheck; 100% coverage.

**Non-negotiables:** English only. No gate bypass. Coherent commits. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Verification evidence (live, 2026-06-10)

- **gitleaks** `gitleaks/gitleaks` tag `v8.30.1` → `gitleaks_8.30.1_linux_x64.tar.gz`, `..._linux_arm64.tar.gz`, `..._darwin_x64.tar.gz`, `..._darwin_arm64.tar.gz`. tar root = `LICENSE README.md gitleaks` → member `gitleaks`, strip 0. amd64 token = `x64`, arm64 = `arm64`. brew core. All 4 platforms.
- **vale** `errata-ai/vale` tag `v3.14.2` → `vale_3.14.2_Linux_64-bit.tar.gz`, `..._Linux_arm64.tar.gz`, `..._macOS_64-bit.tar.gz`, `..._macOS_arm64.tar.gz`. tar root = `LICENSE README.md vale` → member `vale`, strip 0. amd64 token = `64-bit`, arm64 = `arm64`; OS words `Linux`/`macOS`. brew core. All 4 platforms.
- **broot** `Canop/broot` tag `v1.57.0` → one combined `broot_1.57.0.zip` containing `<target>/broot` per platform: `x86_64-unknown-linux-gnu/broot`, `aarch64-unknown-linux-gnu/broot`, `aarch64-apple-darwin/broot` (NO `x86_64-apple-darwin` → Intel-Mac falls to brew). brew core. asset has no version token; the zip filename carries `{ver}`.

Categories: gitleaks → `security` (new), vale → `dev`, broot → `nav`.

---

## Task 1: Add `x64` and `bits` arch tokens

**Files:**
- Modify: `installer/assets.py`
- Test: `tests/test_assets.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_assets.py` (it already imports `arch_tokens`, `render_asset`):

```python
def test_x64_and_bits_tokens_per_arch():
    amd64 = arch_tokens("amd64")
    arm64 = arch_tokens("arm64")
    assert (amd64.x64, amd64.bits) == ("x64", "64-bit")
    assert (arm64.x64, arm64.bits) == ("arm64", "arm64")


def test_render_uses_x64_and_bits_tokens():
    amd64 = arch_tokens("amd64")
    assert render_asset("gitleaks_{ver}_linux_{arch.x64}.tar.gz", "8.30.1", amd64) == (
        "gitleaks_8.30.1_linux_x64.tar.gz"
    )
    assert render_asset("vale_{ver}_Linux_{arch.bits}.tar.gz", "3.14.2", amd64) == (
        "vale_3.14.2_Linux_64-bit.tar.gz"
    )
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_assets.py -q`
Expected: FAIL — `ArchTokens` has no `x64`/`bits`.

- [ ] **Step 3: Implement**

In `installer/assets.py`, add the two fields to the `ArchTokens` dataclass (after `suffix`):

```python
@dataclass(frozen=True)
class ArchTokens:
    machine: str  # x86_64 | aarch64
    deb: str  # amd64 | arm64
    go: str  # amd64 | arm64
    suffix: str  # x86_64 | arm64
    x64: str  # x64 | arm64  (gitleaks-style)
    bits: str  # 64-bit | arm64  (vale-style)
```

And extend the `_TOKENS` mapping:

```python
_TOKENS = {
    "amd64": ArchTokens(
        machine="x86_64", deb="amd64", go="amd64", suffix="x86_64", x64="x64", bits="64-bit"
    ),
    "arm64": ArchTokens(
        machine="aarch64", deb="arm64", go="arm64", suffix="arm64", x64="arm64", bits="arm64"
    ),
}
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_assets.py -q`
Expected: PASS (existing token/render tests unaffected — new fields don't change existing templates).

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`

```bash
git add installer/assets.py tests/test_assets.py
git commit -m "feat: add x64 and bits arch tokens for gitleaks/vale-style assets

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Add gitleaks and vale (registry data)

**Files:**
- Modify: `installer/registry.toml`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Bump the count test to 46 + add a resolution test (failing first)**

In `tests/test_registry.py`, rename `test_registry_has_forty_four_unique_tools_and_cmds` → and set 46:

```python
def test_registry_has_forty_six_unique_tools_and_cmds() -> None:
    tools = load_tools(REGISTRY)
    ids = [t.id for t in tools]
    cmds = [t.cmd for t in tools]
    assert len(ids) == 46
    assert len(ids) == len(set(ids))
    assert len(cmds) == len(set(cmds))
```

Append:

```python
def test_gitleaks_and_vale_use_new_arch_tokens() -> None:
    tools = {t.id: t for t in load_tools(REGISTRY)}
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)

    gl_linux = resolve_methods(tools["gitleaks"], linux)
    assert [m.kind for m in gl_linux] == ["github_release", "brew"]
    assert gl_linux[0].params["asset"] == "gitleaks_{ver}_linux_{arch.x64}.tar.gz"
    assert gl_linux[0].params["member"] == "gitleaks"
    assert resolve_methods(tools["gitleaks"], macos)[0].params["asset"] == (
        "gitleaks_{ver}_darwin_{arch.x64}.tar.gz"
    )

    vale_linux = resolve_methods(tools["vale"], linux)
    assert [m.kind for m in vale_linux] == ["github_release", "brew"]
    assert vale_linux[0].params["asset"] == "vale_{ver}_Linux_{arch.bits}.tar.gz"
    assert resolve_methods(tools["vale"], macos)[0].params["asset"] == (
        "vale_{ver}_macOS_{arch.bits}.tar.gz"
    )
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_registry.py -q`
Expected: FAIL — count 44≠46; gitleaks/vale don't exist.

- [ ] **Step 3: Append the two entries to `installer/registry.toml`**

```toml
[[tool]]
id = "gitleaks"
name = "gitleaks"
category = "security"
cmd = "gitleaks"
priority = "P3"
audience = "both"
desc = "Detect hardcoded secrets in git repos and files"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "gitleaks/gitleaks"
asset = "gitleaks_{ver}_linux_{arch.x64}.tar.gz"
member = "gitleaks"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "gitleaks/gitleaks"
asset = "gitleaks_{ver}_darwin_{arch.x64}.tar.gz"
member = "gitleaks"
strip = 0
[[tool.method]]
kind = "brew"
formula = "gitleaks"

[[tool]]
id = "vale"
name = "Vale"
category = "dev"
cmd = "vale"
priority = "P3"
audience = "both"
desc = "Syntax-aware linter for prose and documentation"
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "errata-ai/vale"
asset = "vale_{ver}_Linux_{arch.bits}.tar.gz"
member = "vale"
strip = 0
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "errata-ai/vale"
asset = "vale_{ver}_macOS_{arch.bits}.tar.gz"
member = "vale"
strip = 0
[[tool.method]]
kind = "brew"
formula = "vale"
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_registry.py -q`
Expected: PASS (count 46; gitleaks/vale resolve github_release→brew with the new tokens; the stranding guard still passes).

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add gitleaks and vale (x64/bits arch tokens; registry 44->46)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Selective `.zip` extraction (extract only the member)

**Files:**
- Modify: `installer/download.py`
- Test: `tests/test_download.py`

- [ ] **Step 1: Update the existing zip test to expect the member in the unzip argv**

In `tests/test_download.py`, in `test_github_release_zip_uses_unzip_and_ignores_strip`, change the `extract` expectation's unzip line to include the quoted member. The full expected `extract` becomes:

```python
    extract = (
        'tmp=$(mktemp) && trap \'rm -f "$tmp"\' EXIT'
        f' && curl -fsSL -o "$tmp" -- {shlex.quote(url)}'
        f' && unzip -q -o "$tmp" {shlex.quote("deno")} -d {shlex.quote(str(opt))}'
    )
```

(The member for that test is `deno`.)

- [ ] **Step 2: Add a test proving a NESTED member is extracted selectively**

Append to `tests/test_download.py`:

```python
def test_zip_extracts_only_the_nested_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, runner = _record()
    bin_dir = tmp_path / "bin"
    method = Method(
        kind="github_release",
        params={
            "repo": "Canop/broot",
            "asset": "broot_{ver}.zip",
            "member": "{arch.machine}-unknown-linux-gnu/broot",
            "archive": "zip",
            "bin_dir": str(bin_dir),
        },
    )
    install_download(method, _ctx(runner, tmp_version="v1.57.0"))
    opt = tmp_path / ".local" / "opt" / "broot"
    member = "x86_64-unknown-linux-gnu/broot"  # {arch.machine} rendered for amd64
    binary = opt / member
    url = "https://github.com/Canop/broot/releases/download/v1.57.0/broot_1.57.0.zip"
    extract = (
        'tmp=$(mktemp) && trap \'rm -f "$tmp"\' EXIT'
        f' && curl -fsSL -o "$tmp" -- {shlex.quote(url)}'
        f' && unzip -q -o "$tmp" {shlex.quote(member)} -d {shlex.quote(str(opt))}'
    )
    assert calls[0] == ["sh", "-c", extract]
    assert ["chmod", "+x", str(binary)] in calls
    assert ["ln", "-sf", str(binary), str(bin_dir / "broot")] in calls
```

- [ ] **Step 3: Run, confirm FAIL**

Run: `uv run pytest tests/test_download.py -q`
Expected: FAIL — the executor still does whole-archive `unzip -q -o "$tmp" -d <opt>` (no member).

- [ ] **Step 4: Implement selective extraction**

In `installer/download.py`, in the `archive == "zip"` branch, add the quoted member to the unzip command. The member is already computed as `member` in `install_download`; add `quoted_member = shlex.quote(member)` alongside `quoted_opt`, and change the zip `extract` to:

```python
    if _opt_str(method, "archive") == "zip":
        extract = (
            "tmp=$(mktemp) && trap 'rm -f \"$tmp\"' EXIT"
            f' && curl -fsSL -o "$tmp" -- {quoted_url}'
            f' && unzip -q -o "$tmp" {quoted_member} -d {quoted_opt}'
        )
```

(Place `quoted_member = shlex.quote(member)` where `quoted_opt`/`quoted_url` are defined, so it is available to the zip branch. The tar branch is unchanged.)

- [ ] **Step 5: Run, confirm PASS**

Run: `uv run pytest tests/test_download.py -q`
Expected: PASS — both the flat (`deno`) and nested (`broot`) members extract selectively; tar.gz tests unchanged.

- [ ] **Step 6: Validate, test, commit**

Run: `make validate && make test`

```bash
git add installer/download.py tests/test_download.py
git commit -m "feat: extract only the member from .zip archives (selective unzip)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Add broot (registry data)

**Files:**
- Modify: `installer/registry.toml`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Bump count to 47 + add a resolution test (failing first)**

In `tests/test_registry.py`, rename `test_registry_has_forty_six_unique_tools_and_cmds` → and set 47:

```python
def test_registry_has_forty_seven_unique_tools_and_cmds() -> None:
    tools = load_tools(REGISTRY)
    ids = [t.id for t in tools]
    cmds = [t.cmd for t in tools]
    assert len(ids) == 47
    assert len(ids) == len(set(ids))
    assert len(cmds) == len(set(cmds))
```

Append:

```python
def test_broot_is_selective_zip_with_nested_member() -> None:
    broot = next(t for t in load_tools(REGISTRY) if t.id == "broot")
    linux = Platform(os="debian", arch="amd64", immutable=False, has_brew=True)
    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    lin = resolve_methods(broot, linux)
    assert [m.kind for m in lin] == ["github_release", "brew"]
    assert lin[0].params["asset"] == "broot_{ver}.zip"
    assert lin[0].params["archive"] == "zip"
    assert lin[0].params["member"] == "{arch.machine}-unknown-linux-gnu/broot"
    mac = resolve_methods(broot, macos)
    assert mac[0].params["member"] == "{arch.machine}-apple-darwin/broot"
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_registry.py -q`
Expected: FAIL — count 46≠47; broot doesn't exist.

- [ ] **Step 3: Append the broot entry to `installer/registry.toml`**

```toml
[[tool]]
id = "broot"
name = "broot"
category = "nav"
cmd = "broot"
priority = "P3"
audience = "both"
desc = "Interactive tree view and fuzzy file navigator"
# One combined multi-platform zip; we extract only this platform's binary (selective unzip).
# No x86_64-apple-darwin in the archive -> Intel Macs fall through to brew.
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "Canop/broot"
asset = "broot_{ver}.zip"
member = "{arch.machine}-unknown-linux-gnu/broot"
archive = "zip"
[[tool.method]]
kind = "github_release"
os = ["macos"]
repo = "Canop/broot"
asset = "broot_{ver}.zip"
member = "{arch.machine}-apple-darwin/broot"
archive = "zip"
[[tool.method]]
kind = "brew"
formula = "broot"
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_registry.py -q`
Expected: PASS (count 47; broot resolves github_release→brew with the selective-zip member; stranding guard passes — brew backstops Intel-Mac).

- [ ] **Step 5: Validate, test, commit**

Run: `make validate && make test`

```bash
git add installer/registry.toml tests/test_registry.py
git commit -m "feat: add broot via selective-zip extraction (registry 46->47)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Document the new tools

**Files:**
- Modify: `README.md` (the "Available tools" table)

- [ ] **Step 1: Update the catalog**

In `README.md`'s "Available tools" table:
- Add `vale` to the `dev` row.
- Add `broot` to the `nav` row.
- Add a new `security` row: `| security | `gitleaks` |`.

- [ ] **Step 2: Validate and commit**

Run: `make validate && make test`

```bash
git add README.md
git commit -m "docs: list gitleaks, vale, broot in the tool catalog

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final check

- `make validate && make test` green at 100% on the final tree.
- Registry has 47 unique tools and 47 unique cmds.
- `.zip` archives extract only the member (verified for flat `deno` and nested `broot`).
- Update `roadmap-status.md` memory: x64/bits tokens done (gitleaks, vale); selective-zip done (broot); registry at 47.
