# Catalog Dependency Audit — 2026-06-22

## Method and Scope

Every tool in `installer/registry.toml` (50 tools as of this audit) was examined for
(1) inter-tool install dependencies — whether a catalog tool must be present *before*
another can be installed — and (2) npm-package candidacy — whether the tool's upstream
is genuinely distributed as an npm package whose `bin` provides the tool's `cmd`.
For any suspected npm candidate, a live `curl` probe against
`https://registry.npmjs.org/<pkg>/latest` was run to confirm name and bin entries.
The integrity guards `requires_integrity_errors` and `test_shipped_node_tools_require_pnpm`
were confirmed green before and after the audit.

---

## Per-Tool Determinations

### Standalone single-binary tools — no inter-tool install dependencies, not npm packages

These tools ship pre-compiled standalone binaries (Rust, Go, or C) via GitHub Releases
and/or package managers. None requires another catalog tool to install, and none is
primarily distributed as an npm package.

| Tool ID     | Category | Distribution          | Note                                                    |
|-------------|----------|-----------------------|---------------------------------------------------------|
| rg          | search   | github_release / brew | Rust binary (BurntSushi/ripgrep)                        |
| jq          | data     | dnf/apt/pacman / brew | C binary, distro-packaged                               |
| fd          | search   | github_release / brew | Rust binary (sharkdp/fd)                                |
| bat         | view     | github_release / brew | Rust binary (sharkdp/bat)                               |
| sd          | text     | github_release / brew | Rust binary (chmln/sd)                                  |
| delta       | git      | github_release / brew | Rust binary (dandavison/delta)                          |
| eza         | view     | github_release / brew | Rust binary (eza-community/eza)                         |
| zoxide      | nav      | github_release / brew | Rust binary (ajeetdsouza/zoxide)                        |
| fzf         | search   | github_release / brew | Go binary (junegunn/fzf)                                |
| lazygit     | git      | github_release / brew | Go binary (jesseduffield/lazygit); uses delta at runtime but does NOT require it to install |
| gh          | git      | github_release / brew | Go binary (cli/cli)                                     |
| yq          | data     | github_release / brew | Go binary (mikefarah/yq), raw download                  |
| starship    | shell    | github_release / brew | Rust binary (starship/starship)                         |
| direnv      | shell    | github_release / brew | Go binary (direnv/direnv), raw download                 |
| just        | dev      | github_release / brew | Rust binary (casey/just)                                |
| ruff        | dev      | github_release / brew | Rust binary (astral-sh/ruff)                            |
| dust        | sysinfo  | github_release / brew | Rust binary (bootandy/dust); npm pkg `dust@0.x` exists but is an unrelated project |
| hyperfine   | dev      | github_release / brew | Rust binary (sharkdp/hyperfine)                         |
| bottom      | sysinfo  | github_release / brew | Rust binary (ClementTsang/bottom), cmd=btm              |
| gum         | shell    | github_release / brew | Go binary (charmbracelet/gum)                           |
| glow        | view     | github_release / brew | Go binary (charmbracelet/glow)                          |
| xh          | net      | github_release / brew | Rust binary (ducaale/xh)                                |
| difftastic  | git      | github_release / brew | Rust binary (Wilfred/difftastic), cmd=difft             |
| gitui       | git      | github_release / brew | Rust binary (extrawurst/gitui)                          |
| lazydocker  | docker   | github_release / brew | Go binary (jesseduffield/lazydocker)                    |
| dive        | docker   | github_release / brew | Go binary (wagoodman/dive)                              |
| duf         | sysinfo  | github_release / brew | Go binary (muesli/duf)                                  |
| hexyl       | view     | github_release / brew | Rust binary (sharkdp/hexyl)                             |
| miller      | data     | github_release / brew | C binary (johnkerl/miller), cmd=mlr                     |
| shfmt       | dev      | github_release / brew | Go binary (mvdan/sh), raw download; npm pkg `shfmt` exists but has no `bin` entry |
| tealdeer    | dev      | github_release / brew | Rust binary (dbrgn/tealdeer), cmd=tldr                  |
| fx          | data     | github_release / brew | Go binary (antonmedv/fx), raw download; npm pkg `fx` confirmed same author but primary distribution is standalone binary |
| dasel       | data     | github_release / brew | Go binary (TomWright/dasel), raw download               |
| gron        | data     | github_release / brew | Go binary (tomnomnom/gron); npm pkg `gron@4.x` is a different project (fgribreau/gron) |
| aichat      | ai       | github_release / brew | Rust binary (sigoden/aichat); npm pkg `aichat` has no `bin` entries |
| deno        | runtime  | github_release / brew | Rust binary (denoland/deno), zip archive                |
| procs       | sysinfo  | github_release / brew | Rust binary (dalance/procs), zip archive; npm pkg `procs` name collision, unrelated package |
| ast-grep    | search   | github_release / brew | Rust binary (ast-grep/ast-grep), cmd=ast-grep; npm `@ast-grep/cli` exists from same repo but primary distribution is standalone binary |
| jless       | data     | github_release / brew | Rust binary (PaulJuliusMartinez/jless), zip archive     |
| gitleaks    | security | github_release / brew | Go binary (gitleaks/gitleaks)                           |
| vale        | dev      | github_release / brew | Go binary (errata-ai/vale)                              |
| broot       | nav      | github_release / brew | Rust binary (Canop/broot), zip archive                  |

### Script-installed package managers and runtimes — self-bootstrapping, no inter-tool install dependencies

| Tool ID | Category | Distribution  | Note                                                           |
|---------|----------|---------------|----------------------------------------------------------------|
| uv      | pkg-mgr  | script / brew | Downloads its own binary via astral.sh installer script        |
| brew    | pkg-mgr  | script        | Bootstraps itself; macOS and Linux variants both self-contained |
| bun     | runtime  | script / brew | Downloads its own binary via bun.sh installer script           |
| pnpm    | pkg-mgr  | script / brew | Downloads its own binary via get.pnpm.io installer script      |
| fnm     | runtime  | script / brew | Downloads its own binary via fnm.vercel.app installer script   |

### GUI editors — app/cask installs, no inter-tool install dependencies

| Tool ID | Category | Distribution | Note                                                |
|---------|----------|--------------|-----------------------------------------------------|
| vscode  | editor   | app / cask   | Direct .zip download or Homebrew Cask on macOS only |
| sublime | editor   | app / cask   | Direct .zip download or Homebrew Cask on macOS only |

### Node (npm) tools — require pnpm

| Tool ID | Category | Distribution | Note                                                                  |
|---------|----------|--------------|-----------------------------------------------------------------------|
| mmdc    | diagram  | node         | `@mermaid-js/mermaid-cli` on npm, confirmed bin=`mmdc`; requires pnpm |

---

## Live npm Checks Performed

The following `curl` probes were run during this audit:

| npm package queried       | Result                                                                    | Conclusion                                             |
|---------------------------|---------------------------------------------------------------------------|--------------------------------------------------------|
| `fx`                      | name=fx, bin=[fx], repo=github.com/antonmedv/fx                           | Same author as registry tool, but primary dist is binary; NOT added |
| `aichat`                  | name=aichat, bin=[] (no bin)                                              | Not an npm-installable tool                            |
| `shfmt`                   | name=shfmt, bin=[] (no bin)                                               | Not an npm-installable tool                            |
| `lazygit`                 | name=lazygit, bin=[] (no bin)                                             | Not an npm-installable tool                            |
| `gitleaks`                | name=gitleaks, bin=[] (no bin)                                            | Not an npm-installable tool                            |
| `ast-grep`                | name=ast-grep@0.1.0, repo=github.com/azz/ast-grep                        | DIFFERENT project from catalog tool; not the same      |
| `@ast-grep/cli`           | name=@ast-grep/cli, bin=[sg, ast-grep], repo=github.com/ast-grep/ast-grep | Correct repo but primary dist is standalone binary; NOT added |
| `gron`                    | name=gron@4.4.0, repo=github.com/fgribreau/gron                          | DIFFERENT project from catalog (tomnomnom/gron); not the same |
| `dust`                    | (name collision check; npm `dust` is unrelated)                           | Not applicable                                         |
| `procs`                   | name=procs, bin=[procs]                                                   | Name collision; unrelated npm package                  |

---

## Findings

**No additional registry data was warranted.**

`mmdc` remains the sole `node` method tool in the catalog, and it already correctly
declares `requires = ["pnpm"]`. No other catalog tool is distributed primarily as
an npm package (several exist on npm incidentally, but all have standalone binary
distributions that are the canonical install path). No inter-tool install dependencies
exist beyond the `mmdc → pnpm` relationship already recorded: every other tool is
self-bootstrapping via its own installer script, a pre-built binary from GitHub Releases,
or a package manager.

Integrity guards confirmed green (53 tests pass):
- `test_shipped_registry_requires_all_resolve` — all `requires` IDs resolve
- `test_shipped_node_tools_require_pnpm` — every `node` method tool requires pnpm
- No cycles detected by `DependencyCycleError` path
